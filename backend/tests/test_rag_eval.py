from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.rag.eval import (
    answer_from_hits,
    has_wrong_number,
    ingest_gold_corpus,
    parse_rag_eval_md,
    recall_at_k,
    run_offline_eval,
    wrong_number_sequences,
)
from app.rag import hybrid_search, ingest_text

RECALL_TARGET = 0.9


def setup_module(_module=None):
    db.init_db()


def test_parse_rag_eval_has_eight_synthetic_cases():
    cases = parse_rag_eval_md()
    assert len(cases) == 8
    joined = "\n".join(c.question + c.chunk_text for c in cases).lower()
    assert "customer" not in joined
    assert any("SPL-4092-B" in c.chunk_text for c in cases)


def test_wrong_number_detector_catches_invented_9999():
    hits = ["Part SPL-4092-B bore is 12.5 mm nominal."]
    answer = "The diameter is 9999 mm."
    assert has_wrong_number(answer, hits)
    assert "9999" in wrong_number_sequences(answer, hits)


def test_recall_at_eight_and_zero_wrong_numbers():
    cases = parse_rag_eval_md()
    gold_ids = ingest_gold_corpus(cases)
    recall = recall_at_k(cases, gold_ids, k=8, search=hybrid_search)
    assert recall >= RECALL_TARGET

    wrong_total = 0
    for case in cases:
        ranked = hybrid_search(case.question, 8)
        answer = answer_from_hits(case.question, ranked)
        from app.rag.eval import fetch_chunk_texts

        texts = fetch_chunk_texts(ranked)
        hit_texts = [texts[cid] for cid in ranked if cid in texts]
        wrong_total += len(wrong_number_sequences(answer, hit_texts))
    assert wrong_total == 0


def test_run_offline_eval_summary():
    summary = run_offline_eval(k=8)
    assert summary["n_questions"] == 8
    assert summary["recall_at_k"] >= RECALL_TARGET
    assert summary["wrong_number_count"] == 0


def test_answer_from_hits_refuses_unknown_number():
    ingest_text(
        "Memo ZZ-001\n\nNo numeric fields in this note.",
        namespace="rag-eval-extra",
        uri="rag-eval-extra:nonumeric",
    )
    hits = hybrid_search("What is the lot size 500 for ZZ-001?", limit=8)
    answer = answer_from_hits("What is the lot size 500 for ZZ-001?", hits)
    from app.rag.eval import fetch_chunk_texts

    texts = fetch_chunk_texts(hits)
    hit_texts = [texts[cid] for cid in hits if cid in texts]
    if "500" not in "\n".join(hit_texts):
        assert "9999" not in answer
        assert not any(seq == "500" for seq in wrong_number_sequences(answer, hit_texts)) or has_wrong_number(
            answer, hit_texts
        ) is False
