from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.gemini_client import _payload
from app.intent import CASES, ROUTES, classify, planned_tools, route_for
from app.tools.registry import TOOL_SCHEMAS

SEND_TOOLS = {"send_email"}
DRAFT_TOOLS = {"draft_email", "forward_email", "reply_with_attachments", "task_for_gemini"}

# phrase, kind, tools that must be allowed, tools that must never be allowed
CONFLICTS: list[tuple[str, str, tuple[str, ...], tuple[str, ...]]] = [
    ("open Neha's last email", "mail_read", ("read_email",), ("draft_email", "search_emails", "send_email", "forward_email")),
    ("what did Deepak write", "mail_read", ("read_email",), ("draft_email", "search_emails")),
    ("write an email to Deepak", "mail_draft", (), ("send_email", "search_emails", "research")),
    ("draft an email to ops@example.com", "mail_draft", (), ("send_email",)),
    ("reply to the last email", "mail_draft", (), ("send_email",)),
    ("read the last email and reply", "mail_read", ("read_email",), ("send_email",)),
    ("write to Deepak", "chat", (), ("draft_email", "send_email")),
    ("check mail from Neha", "mail_search", ("search_emails",), ("read_email", "draft_email")),
    ("show Neha's unread mail", "mail_search", ("search_emails",), ("draft_email", "read_email")),
    ("search my mail", "mail_search", ("search_emails",), ("research", "draft_email")),
    ("search emails from Deepak", "mail_search", ("search_emails",), ("research",)),
    ("search the web for Paladon", "research", ("research",), ("search_emails", "read_email")),
    ("search for Paladon", "research", ("research",), ("search_emails",)),
    ("what's on", "briefing", ("get_briefing",), ("list_calendar", "search_emails")),
    ("what's on my calendar", "calendar_list", ("list_calendar",), ("get_briefing", "search_emails")),
    ("when is my next meeting", "calendar_list", ("list_calendar",), ("get_briefing", "create_calendar_event")),
    ("what's tomorrow", "calendar_list", ("list_calendar",), ("get_briefing", "create_calendar_event")),
    ("what do I have tomorrow", "calendar_list", ("list_calendar",), ("get_briefing",)),
    ("what's in my inbox", "mail_search", ("search_emails",), ("get_briefing", "read_email")),
    ("forward this to Pratik", "mail_forward", ("forward_email",), ("task_for_gemini", "send_email")),
    ("forward this to Gemini", "gemini", ("task_for_gemini",), ("forward_email", "draft_email")),
    ("save the piston PDF", "mail_save", ("save_mail_attachments",), ("drive_upload", "draft_email")),
    ("save to Drive", "drive_upload", ("drive_upload",), ("save_mail_attachments",)),
    ("open the last email", "mail_read", ("read_email",), ("show_artifact", "create_spreadsheet")),
    ("open the spreadsheet", "sheet_open", ("show_artifact",), ("read_email", "create_spreadsheet")),
    ("make a spreadsheet of blockers", "sheet_create", ("create_spreadsheet",), ("show_artifact", "read_email", "ensure_shop_sheet")),
    ("open DPIS000377", "chat", (), ("read_email", "draft_email", "research")),
    ("view the piston PDF", "chat", (), ("read_email", "save_mail_attachments")),
    ("don't reply", "chat", (), ("draft_email", "read_email")),
    ("aluminium prices in India", "research", ("research",), ("search_emails", "get_briefing")),
    ("book a call with Rahul at 4pm", "calendar_create", ("create_calendar_event",), ("list_calendar", "draft_email")),
    ("write meeting notes", "doc_create", ("create_document",), ("draft_email", "create_spreadsheet")),
    ("what's in this RFQ", "rfq_reason", ("reason_rfq",), ("cnc_suggest", "send_email", "draft_email", "create_calendar_event")),
    ("treat this as an RFQ from Deepak", "rfq_reason", ("reason_rfq",), ("cnc_suggest", "send_email")),
    ("quote on this drawing", "rfq_reason", ("reason_rfq",), ("cnc_suggest",)),
    ("write a program from scratch", "cnc_suggest", ("cnc_suggest",), ("reason_rfq", "send_email", "draft_email")),
    ("suggest G-code for this", "cnc_suggest", ("cnc_suggest",), ("reason_rfq", "send_email")),
    ("CNC program for this", "cnc_suggest", ("cnc_suggest",), ("reason_rfq",)),
    ("what's the OEE", "shop_read", ("read_shop_sheet",), ("update_shop_sheet", "create_spreadsheet", "send_email")),
    ("create a shop log", "shop_create", ("ensure_shop_sheet",), ("create_spreadsheet", "bind_shop_sheet")),
    ("bind this google sheet", "shop_bind", ("bind_shop_sheet",), ("create_spreadsheet", "update_shop_sheet")),
    ("set CNC-1 OEE to 92", "shop_write", ("update_shop_sheet",), ("read_shop_sheet", "send_email", "create_spreadsheet")),
    ("write 88 in B2", "shop_write", ("update_shop_sheet",), ("create_spreadsheet", "draft_email")),
]

_MAIL_OPEN = re.compile(r"\b(mail|email|e-mail|inbox|gmail|message|letter)\b", re.I)
_DRAWING_HINT = re.compile(r"\b(pdf|drawing|drawings|attachment|attachments|dpis|rfnw|piston)\b|\.[a-z]{3,4}\b", re.I)
_DRAWING_CODE = re.compile(r"\b(?:open|view|show)\s+(?:the\s+)?([A-Za-z]*\d[A-Za-z0-9._-]*)\b", re.I)
_VIEW_VERB = re.compile(r"\b(view|open|show)\b", re.I)

VIEWER_CASES: list[tuple[str, bool]] = [
    ("open the last email", False),
    ("open Neha's last email", False),
    ("open mail from Neha", False),
    ("open DPIS000377", True),
    ("view the piston PDF", True),
    ("open the piston drawing", True),
    ("show the last email", False),
    ("open the spreadsheet", False),
]


def is_view_command(message: str) -> bool:
    if not _VIEW_VERB.search(message):
        return False
    if _MAIL_OPEN.search(message) and not _DRAWING_HINT.search(message):
        return False
    return bool(_DRAWING_HINT.search(message) or _DRAWING_CODE.search(message) or re.search(r"\bpiston\b", message, re.I))


def test_every_case_matches():
    fails = []
    for phrase, want in CASES:
        got = classify(phrase).kind
        if got != want:
            fails.append((phrase, want, got))
    assert not fails, fails


def test_every_kind_has_a_route():
    kinds = {kind for _phrase, kind in CASES}
    missing = sorted(kind for kind in kinds if kind not in ROUTES)
    assert not missing, missing


def test_conflicts():
    fails = []
    for phrase, kind, need, forbid in CONFLICTS:
        got = classify(phrase).kind
        tools = planned_tools(phrase)
        if got != kind:
            fails.append((phrase, "kind", kind, got))
            continue
        for name in need:
            if name not in tools:
                fails.append((phrase, "missing", name, tools))
        for name in forbid:
            if name in tools:
                fails.append((phrase, "forbidden", name, tools))
        if kind.startswith("mail_") and "send_email" in tools:
            fails.append((phrase, "send on mail route", tools))
    assert not fails, fails


def test_read_cannot_draft():
    intent = classify("open Neha's last email")
    route = route_for(intent.kind)
    assert intent.kind == "mail_read"
    assert intent.person == "Neha"
    assert intent.last is True
    assert route.tools == ("read_email",)
    assert "draft_email" not in route.tools
    assert planned_tools("open Neha's last email") == ("read_email",)
    assert planned_tools("reply to Neha") == ()
    assert planned_tools("how are you") == ()


def test_write_vs_wrote():
    assert classify("what did Deepak write").kind == "mail_read"
    assert classify("write to Deepak").kind == "chat"
    assert classify("write back to Neha").kind == "chat"
    assert classify("write an email to Deepak").kind == "mail_draft"
    assert classify("write meeting notes").kind == "doc_create"


def test_gemini_vs_forward():
    assert classify("forward this to Pratik").kind == "mail_forward"
    assert classify("forward this to Gemini").kind == "gemini"
    assert "forward_email" not in planned_tools("forward this to Gemini")
    assert "task_for_gemini" not in planned_tools("forward this to Pratik")


def test_briefing_vs_calendar_vs_inbox():
    assert classify("what's on").kind == "briefing"
    assert classify("what's on my calendar").kind == "calendar_list"
    assert classify("what's on my schedule").kind == "calendar_list"
    assert classify("when is my next meeting").kind == "calendar_list"
    assert classify("any meetings today").kind == "calendar_list"
    assert classify("what's tomorrow").kind == "calendar_list"
    assert classify("what do I have tomorrow").kind == "calendar_list"
    assert classify("any meetings today").query == "today"
    assert classify("what's tomorrow").query == "tomorrow"
    assert classify("what's on").kind == "briefing"
    assert classify("write meeting notes").kind == "doc_create"
    assert classify("what's in my inbox").kind == "mail_search"
    assert classify("what's in that email").kind == "mail_read"


def test_gemini_tool_config_allowlist():
    phrases = {
        "open Neha's last email": ["read_email"],
        "check my mail": ["search_emails"],
        "search the web for Paladon": ["research"],
        "draft an email to ops@example.com": [],
    }
    decls = TOOL_SCHEMAS
    for phrase, allowed in phrases.items():
        tools = list(planned_tools(phrase))
        if not tools:
            assert allowed == []
            continue
        body = _payload(
            [{"role": "user", "content": phrase}],
            decls,
            False,
            None,
            tools,
        )
        cfg = body["toolConfig"]["functionCallingConfig"]
        names = [item["name"] for item in body["tools"][0]["functionDeclarations"]]
        assert cfg["mode"] == "ANY", phrase
        assert cfg["allowedFunctionNames"] == allowed, (phrase, cfg)
        assert set(names) == set(allowed), (phrase, names)
        assert not (set(names) & SEND_TOOLS), phrase
        if phrase == "open Neha's last email":
            assert "draft_email" not in names


def test_heuristic_obeys_route():
    from app import db
    from app.agent import _heuristic_tools

    db.init_db()

    prefs = {
        "email_enabled": True,
        "calendar_enabled": True,
        "files_enabled": True,
        "research_enabled": True,
    }
    checks = (
        ("open Neha's last email", ["read_email"]),
        ("what did Deepak write", ["read_email"]),
        ("check my mail", ["search_emails"]),
        ("check mail from Neha", ["search_emails"]),
        ("aluminium prices in India", ["research"]),
        ("search the web for Paladon", ["research"]),
        ("what's on my calendar", ["list_calendar"]),
        ("when is my next meeting", ["list_calendar"]),
        ("book a call with Rahul at 4pm", ["create_calendar_event"]),
        ("how are you", []),
        ("brief me", ["get_briefing"]),
        ("don't reply", []),
        ("open DPIS000377", []),
        ("write meeting notes", ["create_document"]),
        ("what's in this RFQ", ["reason_rfq"]),
        ("treat this as an RFQ from Deepak", ["reason_rfq"]),
        ("write a program from scratch", ["cnc_suggest"]),
        ("suggest G-code for this", ["cnc_suggest"]),
        ("what's the OEE", ["read_shop_sheet"]),
        ("create a shop log", ["ensure_shop_sheet"]),
        ("set CNC-1 OEE to 92", ["update_shop_sheet"]),
    )
    fails = []
    for phrase, want in checks:
        names = [call["name"] for call in _heuristic_tools(phrase, prefs, "route-test")]
        if names != want:
            fails.append((phrase, want, names))
        allowed = set(planned_tools(phrase))
        if allowed and any(name not in allowed for name in names):
            fails.append((phrase, "outside allowlist", names))
        if any(name in SEND_TOOLS for name in names):
            fails.append((phrase, "send tool", names))
        if classify(phrase).kind == "mail_read" and any(name in DRAFT_TOOLS for name in names):
            fails.append((phrase, "draft on read", names))
    assert not fails, fails


def test_fill_read_args():
    from app.agent import _fill_tool_args

    args = _fill_tool_args("read_email", {}, "open Neha's last email", {})
    assert args.get("query") == "from:Neha"
    assert args.get("last") is True
    search = _fill_tool_args("search_emails", {}, "check mail from Neha", {})
    assert search.get("query") == "from:Neha"
    today = _fill_tool_args("list_calendar", {}, "any meetings today", {})
    assert today.get("span") == "today"
    assert today.get("days") == 1
    tomorrow = _fill_tool_args("list_calendar", {}, "what's tomorrow", {})
    assert tomorrow.get("span") == "tomorrow"
    week = _fill_tool_args("list_calendar", {}, "what's on my calendar", {})
    assert week.get("days") == 7
    assert not week.get("span")


def test_social_replies():
    from app.agent import _social_reply

    assert "order" in _social_reply("how are you", {"display_name": "Tony"}).lower()
    assert _social_reply("open Neha's last email", {"display_name": "Tony"}) == ""
    assert _social_reply("hello", {"display_name": "Tony"}) == "Yes?"
    assert "will not reply" in _social_reply("don't reply", {"display_name": "Tony"}).lower()


def test_viewer_vs_mail():
    fails = []
    for phrase, want in VIEWER_CASES:
        got = is_view_command(phrase)
        if got != want:
            fails.append((phrase, want, got))
        kind = classify(phrase).kind
        if want:
            if kind != "chat":
                fails.append((phrase, "viewer should stay chat", kind))
        elif _MAIL_OPEN.search(phrase) and not kind.startswith("mail_"):
            fails.append((phrase, "mail phrase should be mail_*", kind))
    assert not fails, fails


def test_no_route_allows_send():
    for kind, route in ROUTES.items():
        assert "send_email" not in route.tools, kind


if __name__ == "__main__":
    tests = [
        test_every_case_matches,
        test_every_kind_has_a_route,
        test_conflicts,
        test_read_cannot_draft,
        test_write_vs_wrote,
        test_gemini_vs_forward,
        test_briefing_vs_calendar_vs_inbox,
        test_gemini_tool_config_allowlist,
        test_heuristic_obeys_route,
        test_fill_read_args,
        test_social_replies,
        test_viewer_vs_mail,
        test_no_route_allows_send,
    ]
    for test in tests:
        test()
        print("ok", test.__name__)
    print(f"passed {len(tests)}  cases {len(CASES)}  conflicts {len(CONFLICTS)}")
