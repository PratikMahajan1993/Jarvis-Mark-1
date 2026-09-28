"""Semantic router classification (offline fallback + heuristics)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.semantic_router import classify


@pytest.mark.parametrize(
    "text,expected_kind",
    [
        ("hey what's up", "casual_chat"),
        ("what is an RFQ", "casual_chat"),
        ("check copper price", "tool_ops"),
        ("what's the OEE", "tool_ops"),
        ("search my inbox for Deepak", "tool_ops"),
        ("draft an email to ops saying hello", "tool_ops"),
        ("quote this drawing", "tool_ops"),
        ("hide the dock", "ui_command"),
    ],
)
def test_router_classification(text, expected_kind):
    result = classify(text)
    assert result.kind == expected_kind, f"'{text}' → {result.kind}, expected {expected_kind}"
