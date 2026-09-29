from app.section_hint import ui_hint


def test_status_stays():
    assert ui_hint("what is the status", None) is None


def test_quote_and_drawing_go_engineering():
    assert ui_hint("quote the attachment", None)["section"] == "engineering"
    assert ui_hint("open the drawing for part 12", None)["section"] == "engineering"


def test_mail_goes_casual_and_back_to_chat_is_explicit():
    assert ui_hint("reply to that email", None)["section"] == "casual"
    assert ui_hint("go back to chat", None) == {"section": "casual", "reason": "explicit"}


def test_ui_command_has_no_hint():
    assert ui_hint("hide the dock", "ui_command") is None
