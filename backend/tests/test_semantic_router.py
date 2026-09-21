from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.intent import classify
from app.semantic_router import _fallback, classify_intent_sync


def test_quote_start_tool_ops_not_vision_fallback():
    message = "Start quote workflow for XYZ drawing. There is no file on the desk yet."
    result = _fallback(message)
    assert result.intent == "tool_ops", message
    assert result.target_agent == "DAT.03", message
    assert result.intent != "vision_task"


def test_look_at_print_stays_vision_fallback():
    result = _fallback("Look at this print")
    assert result.intent == "vision_task"
    assert result.target_agent == "DAT.03"


def test_quote_start_not_rfq_reason_intent():
    message = "Start quote workflow for XYZ drawing"
    assert classify(message).kind != "rfq_reason"
    assert classify("quote on this drawing").kind == "rfq_reason"


def test_rfq_definition_is_casual_chat_fallback():
    cases = [
        "What is an RFQ?",
        "what is an RFQ for a machine shop",
        "explain RFQ",
        "what does RFQ mean",
        "Summarize what an RFQ is for our shop",
    ]
    for message in cases:
        result = _fallback(message)
        assert result.intent == "casual_chat", message
        assert result.target_agent == "RES.01", message


def test_rfq_work_stays_tool_ops_fallback():
    work = [
        "what's in this RFQ",
        "treat this as an RFQ from Deepak",
        "process this RFQ from Deepak",
    ]
    for message in work:
        result = _fallback(message)
        assert result.intent == "tool_ops", message
        assert result.target_agent == "DAT.03", message


def test_rfq_definition_sync_router():
    result = classify_intent_sync("What is an RFQ?")
    assert result.intent == "casual_chat"
    assert result.target_agent == "RES.01"
