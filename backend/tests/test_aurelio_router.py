"""Aurelio route map and score bands. The encoder itself stays offline here."""

from __future__ import annotations

import app.core.router as aurelio
from app.semantic_router import classify_intent_sync


def test_every_route_maps_to_a_coarse_intent() -> None:
    expected = {
        "cad_drawing_task": ("vision_task", "DAT.03"),
        "shop_query": ("tool_ops", "DAT.03"),
        "rfq_quote": ("tool_ops", "DAT.03"),
        "email_read": ("tool_ops", "SEC.02"),
        "email_send": ("tool_ops", "OPS.04"),
        "casual_chat": ("casual_chat", "RES.01"),
        "ui_command": ("ui_command", "SYS"),
    }
    assert set(aurelio.ROUTE_INTENT) == set(expected)
    for route, pair in expected.items():
        assert aurelio.intent_for_route(route) == pair
    for route, samples in aurelio._UTTERANCES.items():
        assert route in aurelio.ROUTE_INTENT
        assert 25 <= len(samples) <= 30


def test_score_bands() -> None:
    assert aurelio.band_for_score(0.8) == "high"
    assert aurelio.band_for_score(0.75) == "medium"
    assert aurelio.band_for_score(aurelio.ROUTE_MIN_SCORE) == "medium"
    assert aurelio.band_for_score(aurelio.ROUTE_MIN_SCORE - 0.01) == "fallback"


def test_medium_shop_score_routes_without_gemini(monkeypatch) -> None:
    monkeypatch.setattr(aurelio, "classify_fast", lambda _text: ("shop_query", 0.70))
    result = classify_intent_sync("what's OEE today")
    assert result.intent == "tool_ops"
    assert result.target_agent == "DAT.03"
    assert result.confidence == 0.70


def test_low_score_falls_through_to_keyword_fallback(monkeypatch) -> None:
    monkeypatch.setattr(aurelio, "classify_fast", lambda _text: ("casual_chat", 0.2))
    monkeypatch.setattr("app.semantic_router.settings.gemini_api_key", "")
    result = classify_intent_sync("explain quantum physics")
    assert result.intent == "casual_chat"
    assert result.confidence < 0.5


def test_missing_encoder_does_not_raise(monkeypatch) -> None:
    monkeypatch.setattr(aurelio, "classify_fast", lambda _text: None)
    monkeypatch.setattr("app.semantic_router.settings.gemini_api_key", "")
    result = classify_intent_sync("hide the dock")
    assert result.intent == "ui_command"
    assert result.target_agent == "SYS"


def test_quote_start_stays_ahead_of_the_encoder(monkeypatch) -> None:
    monkeypatch.setattr(aurelio, "classify_fast", lambda _text: ("cad_drawing_task", 0.95))
    result = classify_intent_sync("quote this drawing")
    assert result.intent == "tool_ops"
    assert result.target_agent == "DAT.03"


def test_unwarmed_encoder_returns_none() -> None:
    assert aurelio.classify_fast("what's the OEE") is None
