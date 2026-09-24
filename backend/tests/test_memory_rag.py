from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import db
from app.memory import forget, search, upsert
from app.tools.registry import execute_tool


def setup_module(_module=None):
    db.init_db()


def test_memory_upsert_search_forget():
    upsert(
        namespace="people",
        key="koso-deepak",
        text="Mr Deepak from KOSO India Pvt Ltd requests machining quotes with drawings.",
        meta={"company": "KOSO"},
    )
    hits = search("KOSO Deepak quote drawings", namespace="people", limit=5)
    assert hits
    assert "KOSO" in hits[0]["text"]
    deleted = forget(namespace="people", key="koso-deepak")
    assert deleted["ok"]
    assert deleted["deleted"] >= 1
    again = search("KOSO Deepak quote drawings", namespace="people", limit=5)
    assert all(hit.get("key") != "koso-deepak" for hit in again)


def test_memory_tools_via_registry():
    result = execute_tool(
        "memory_upsert",
        {"text": "Shop prefers EN8 for shafts unless drawing says otherwise.", "namespace": "profile", "key": "material-default"},
        "mem-test",
    )
    assert result.get("ok")
    found = execute_tool("memory_search", {"query": "EN8 shafts", "namespace": "profile"}, "mem-test")
    assert found.get("ok")
    hits = (found.get("data") or {}).get("hits") or []
    assert hits
    summary = execute_tool("memory_summary", {}, "mem-test")
    assert summary.get("ok")
