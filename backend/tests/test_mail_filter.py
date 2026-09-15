from __future__ import annotations

from app.connectors.mail_filter import (
    extract_domain,
    is_allowlisted,
    should_keep_mail,
)


def test_hard_exclude_spam_and_trash():
    for label in ("SPAM", "TRASH"):
        keep, reason = should_keep_mail({"labels": [label], "sender": "a@b.com", "subject": "Hello"})
        assert not keep, label
        assert reason == "hard_label"


def test_allowlist_vendor_domains():
    samples = (
        "Supabase <noreply@mail.supabase.com>",
        "GitHub <notifications@github.com>",
        "ERPNext <hello@erpnext.com>",
        "Frappe <team@frappe.io>",
        "Google Cloud <cloud-noreply@google.com>",
    )
    for sender in samples:
        assert is_allowlisted(sender), sender
        keep, reason = should_keep_mail(
            {"labels": ["CATEGORY_PROMOTIONS"], "sender": sender, "subject": "50% off sale today"},
        )
        assert keep, sender
        assert reason == "allowlist"


def test_promotions_category_skipped_for_unknown():
    keep, reason = should_keep_mail(
        {
            "labels": ["CATEGORY_PROMOTIONS", "INBOX"],
            "sender": "Shop <deals@random-shop.example>",
            "subject": "Your order update",
        }
    )
    assert not keep
    assert reason == "category"


def test_promo_subject_heuristic():
    keep, reason = should_keep_mail(
        {
            "labels": ["INBOX"],
            "sender": "Marketing <promo@unknown-vendor.example>",
            "subject": "Limited time 40% off — shop now",
        }
    )
    assert not keep
    assert reason == "promo_heuristic"


def test_normal_inbox_kept():
    keep, reason = should_keep_mail(
        {
            "labels": ["INBOX", "UNREAD"],
            "sender": "Priya Shah <priya@northline.example>",
            "subject": "Re: Q3 proposal - need your redlines",
        }
    )
    assert keep
    assert reason == "ok"


def test_extract_domain():
    assert extract_domain("GitHub <notifications@github.com>") == "github.com"
    assert extract_domain("plain@sub.supabase.com") == "sub.supabase.com"
