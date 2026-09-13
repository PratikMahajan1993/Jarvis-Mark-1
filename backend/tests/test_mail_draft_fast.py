from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agent import _extract_email_address
from app.intent import classify
from app.mail_compose import extract_email_address


def test_extract_email_fixes_comma_typo():
    assert _extract_email_address("Draft a small email to pratik.281293@gggg,com") == "pratik.281293@gggg.com"
    assert extract_email_address("mail ops@example.com please") == "ops@example.com"


def test_tight_phrase_required_for_draft():
    assert classify("Draft an email to pratik.281293@gggg,com saying the shop is clear").kind == "mail_draft"
    # "small" breaks the allowlisted starter — must not open compose
    assert classify("Draft a small email to pratik.281293@gggg,com").kind != "mail_draft"
