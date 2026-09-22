"""Offline RAG gold-set evaluation: recall@k and wrong-number guard."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .. import db
from .ingest import ingest_text
from .search import hybrid_search

_EVAL_NS = "rag-eval"
_BLOCK_RE = re.compile(
    r"^##\s+(?P<id>\d+)\s*\n+\*\*Question:\*\*\s*(?P<question>.+?)\n+\*\*Chunk:\*\*\s*\n+```(?:text)?\s*\n(?P<chunk>.+?)```",
    re.MULTILINE | re.DOTALL,
)
_DIGIT_SEQ = re.compile(r"\d+(?:\.\d+)?")
_ASK_FALLBACK = (
    "I do not have that number in the retrieved text; please confirm from the source document."
)


@dataclass(frozen=True)
class GoldCase:
    case_id: str
    question: str
    chunk_text: str


def default_eval_md_path() -> Path:
    return Path(__file__).resolve().parents[3] / "work" / "RAG_EVAL.md"


def parse_rag_eval_md(path: Path | None = None) -> list[GoldCase]:
    text = (path or default_eval_md_path()).read_text(encoding="utf-8")
    cases: list[GoldCase] = []
    for match in _BLOCK_RE.finditer(text):
        chunk = match.group("chunk").strip()
        question = " ".join(match.group("question").split())
        cases.append(
            GoldCase(
                case_id=match.group("id"),
                question=question,
                chunk_text=chunk,
            )
        )
    if len(cases) < 1:
        raise ValueError(f"No gold cases parsed from {path or default_eval_md_path()}")
    return cases


def _chunk_id_for_uri(uri: str) -> str | None:
    with db.connect() as conn:
        row = conn.execute(
            """
            SELECT c.id
            FROM rag_chunks c
            JOIN rag_documents d ON d.id = c.document_id
            WHERE d.namespace = ? AND d.uri = ?
            ORDER BY c.ordinal
            LIMIT 1
            """,
            (_EVAL_NS, uri),
        ).fetchone()
    return row["id"] if row else None


def ingest_gold_corpus(cases: list[GoldCase] | None = None) -> dict[str, str]:
    """Ingest gold chunks; return case_id -> chunk_id."""
    items = cases or parse_rag_eval_md()
    mapping: dict[str, str] = {}
    for case in items:
        uri = f"{_EVAL_NS}:case-{case.case_id}"
        ingest_text(case.chunk_text, namespace=_EVAL_NS, uri=uri, doc_kind="eval")
        chunk_id = _chunk_id_for_uri(uri)
        if not chunk_id:
            raise RuntimeError(f"Gold chunk missing after ingest for case {case.case_id}")
        mapping[case.case_id] = chunk_id
    return mapping


def fetch_chunk_texts(chunk_ids: list[str]) -> dict[str, str]:
    if not chunk_ids:
        return {}
    placeholders = ",".join("?" * len(chunk_ids))
    with db.connect() as conn:
        rows = conn.execute(
            f"SELECT id, text FROM rag_chunks WHERE id IN ({placeholders})",
            chunk_ids,
        ).fetchall()
    return {row["id"]: row["text"] for row in rows}


def digit_sequences(text: str) -> list[str]:
    return _DIGIT_SEQ.findall(text or "")


def wrong_number_sequences(answer: str, hit_texts: list[str]) -> list[str]:
    """Digit sequences in answer that do not appear in any hit text."""
    allowed = "\n".join(hit_texts)
    bad: list[str] = []
    for seq in digit_sequences(answer):
        if seq not in allowed:
            bad.append(seq)
    return bad


def has_wrong_number(answer: str, hit_texts: list[str]) -> bool:
    return bool(wrong_number_sequences(answer, hit_texts))


def answer_from_hits(question: str, hit_ids: list[str]) -> str:
    """Quote numbers only when the exact sequence appears in retrieved text."""
    texts_map = fetch_chunk_texts(hit_ids)
    hit_texts = [texts_map[cid] for cid in hit_ids if cid in texts_map]
    if not hit_texts:
        return _ASK_FALLBACK

    combined = "\n".join(hit_texts)
    q_lower = (question or "").lower()

    best_line = ""
    best_score = -1
    for block in hit_texts:
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            score = sum(1 for tok in re.findall(r"[a-z0-9]{3,}", q_lower) if tok in line.lower())
            if score > best_score:
                best_score = score
                best_line = line

    if not best_line:
        best_line = hit_texts[0].splitlines()[0].strip()

    nums_in_line = digit_sequences(best_line)
    if nums_in_line:
        return f"From the retrieved notes: {best_line}"

    if digit_sequences(question):
        return _ASK_FALLBACK

    return f"From the retrieved notes: {best_line}"


def recall_at_k(
    cases: list[GoldCase],
    gold_chunk_ids: dict[str, str],
    *,
    k: int = 8,
    search: Callable[[str, int], list[str]] = hybrid_search,
) -> float:
    if not cases:
        return 0.0
    hits = 0
    for case in cases:
        gold_id = gold_chunk_ids[case.case_id]
        ranked = search(case.question, k)
        if gold_id in ranked:
            hits += 1
    return hits / len(cases)


def run_offline_eval(
    *,
    k: int = 8,
    eval_md: Path | None = None,
) -> dict[str, float | int]:
    cases = parse_rag_eval_md(eval_md)
    gold_ids = ingest_gold_corpus(cases)
    recall = recall_at_k(cases, gold_ids, k=k)

    wrong_count = 0
    for case in cases:
        ranked = hybrid_search(case.question, k)
        answer = answer_from_hits(case.question, ranked)
        texts_map = fetch_chunk_texts(ranked)
        hit_texts = [texts_map[cid] for cid in ranked if cid in texts_map]
        wrong_count += len(wrong_number_sequences(answer, hit_texts))

    return {
        "recall_at_k": recall,
        "wrong_number_count": wrong_count,
        "n_questions": len(cases),
        "k": k,
    }
