from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent import _heuristic_tools, _social_reply, classify_decision
from app.briefing import build_glance
from app.gemini_client import _payload
from app.intent import CASES, ROUTES, classify, planned_tools, prepare
from app.tools.registry import TOOL_SCHEMAS
from app.understand import normalize_speech, unmatched_clauses

PREFS_ON = {
    "email_enabled": True,
    "calendar_enabled": True,
    "files_enabled": True,
    "research_enabled": True,
    "display_name": "Tony",
}


def test_every_route_kind_has_a_phrase():
    covered = {kind for _phrase, kind in CASES}
    missing = sorted(kind for kind in ROUTES if kind not in covered)
    assert not missing, missing


def test_prepare_wake_and_quotes():
    assert prepare("Jarvis, open Neha's last email") == "open Neha's last email"
    assert prepare("Hey Jarvis check my mail") == "check my mail"
    assert prepare("please read Neha's email") == "read Neha's email"
    curly = "open Neha\u2019s last email"
    assert "'" in prepare(curly)
    assert classify(curly).kind == "mail_read"
    assert classify(curly).person == "Neha"
    assert classify("   OPEN THE LAST EMAIL  ").kind == "mail_read"
    assert classify("OPEN NEHA'S LAST EMAIL").person == "Neha"
    assert classify("").kind == "chat"
    assert classify("   ").kind == "chat"


def test_speech_aliases_then_classify():
    pairs = (
        ("e mail from Neha", "mail_read"),
        ("check my in box", "mail_search"),
        ("what's on my calender", "calendar_list"),
        ("ask gemeni to review the drawing", "gemini"),
        ("make a spread sheet of blockers", "sheet_create"),
    )
    fails = []
    for raw, want in pairs:
        cleaned, _repairs = normalize_speech(raw)
        got = classify(cleaned).kind
        if got != want:
            fails.append((raw, cleaned, want, got))
    assert not fails, fails


def test_yes_no_decisions():
    yes = ("yes", "y", "yeah", "yep", "do it", "send it", "go ahead", "Yes!", "YES")
    no = ("no", "n", "nope", "cancel", "wait", "don't", "No thanks")
    none = ("open the last email", "reply to Neha", "maybe", "brief me", "")
    for phrase in yes:
        assert classify_decision(phrase) is True, phrase
    for phrase in no:
        assert classify_decision(phrase) is False, phrase
    for phrase in none:
        assert classify_decision(phrase) is None, phrase


def test_prefs_off_blocks_mail_heuristic():
    off = {**PREFS_ON, "email_enabled": False}
    names = [call["name"] for call in _heuristic_tools("open Neha's last email", off, "pref-off")]
    assert "read_email" not in names
    cal_off = {**PREFS_ON, "calendar_enabled": False}
    names = [call["name"] for call in _heuristic_tools("what's on my calendar", cal_off, "pref-off")]
    assert "list_calendar" not in names


def test_multi_clause_still_flags_the_rest():
    leftover = unmatched_clauses(
        "open the last email and make a spreadsheet",
        "open the last email and make a spreadsheet",
        ["read_email"],
    )
    families = " ".join(str(item) for item in leftover).lower()
    assert leftover
    assert "sheet" in families or "spreadsheet" in families


def test_toolconfig_for_other_routes():
    samples = (
        "brief me",
        "what's on my calendar",
        "save the piston PDF",
        "put it on Drive",
        "task for Gemini",
    )
    for phrase in samples:
        allowed = list(planned_tools(phrase))
        assert allowed, phrase
        body = _payload(
            [{"role": "user", "content": phrase}],
            TOOL_SCHEMAS,
            False,
            None,
            allowed,
        )
        cfg = body["toolConfig"]["functionCallingConfig"]
        names = [item["name"] for item in body["tools"][0]["functionDeclarations"]]
        assert cfg["mode"] == "ANY"
        assert cfg["allowedFunctionNames"] == allowed
        assert set(names) == set(allowed)
        assert "send_email" not in names
        assert "draft_email" not in names or phrase.startswith("reply") or "draft" in phrase.lower()


def test_glance_does_not_lead_with_unread_count():
    glance = build_glance()
    line = str(glance.get("line") or "").lower()
    whisper = str(glance.get("whisper") or "").lower()
    assert "unread" not in line
    assert "unread" not in whisper or glance.get("key", "").startswith("gemini")


def test_social_does_not_steal_work():
    prefs = {"display_name": "Tony"}
    assert _social_reply("open Neha's last email", prefs) == ""
    assert _social_reply("check my mail", prefs) == ""
    assert _social_reply("brief me", prefs) == ""
    assert _social_reply("how are you", prefs)
    assert "order" in _social_reply("Hey Jarvis how are you", prefs).lower()


def test_punctuation_and_please():
    assert classify("Open Neha's last email.").kind == "mail_read"
    assert classify("check my mail?").kind == "mail_search"
    assert classify("What's in my inbox!").kind == "mail_search"
    assert classify("Jarvis: brief me").kind == "briefing"


if __name__ == "__main__":
    tests = [
        test_every_route_kind_has_a_phrase,
        test_prepare_wake_and_quotes,
        test_speech_aliases_then_classify,
        test_yes_no_decisions,
        test_prefs_off_blocks_mail_heuristic,
        test_multi_clause_still_flags_the_rest,
        test_toolconfig_for_other_routes,
        test_glance_does_not_lead_with_unread_count,
        test_social_does_not_steal_work,
        test_punctuation_and_please,
    ]
    for test in tests:
        test()
        print("ok", test.__name__)
    print(f"passed {len(tests)}")
