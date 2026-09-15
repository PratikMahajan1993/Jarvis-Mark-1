"""Heuristic spam/promo filter for bulk Gmail sync.

Hard-excludes SPAM/TRASH labels. Soft-excludes Gmail category labels unless the
sender matches the vendor/product allowlist. Unknown senders with promo-style
subjects are skipped.
"""

from __future__ import annotations

import re
from typing import Any

# Vendor / product mail the user cares about (subdomains included).
ALLOWLIST_DOMAINS: tuple[str, ...] = (
    "supabase.com",
    "erpnext.com",
    "frappe.io",
    "github.com",
    "google.com",
    "googlemail.com",
)

HARD_EXCLUDE_LABELS = frozenset({"SPAM", "TRASH"})
SOFT_EXCLUDE_LABELS = frozenset({"CATEGORY_PROMOTIONS", "CATEGORY_SOCIAL"})

_PROMO_SUBJECT = re.compile(
    r"\b("
    r"sale|discount|\d+%\s*off|limited time|act now|unsubscribe|"
    r"free shipping|shop now|don'?t miss|exclusive offer|promo|"
    r"newsletter|weekly digest|special offer|clearance"
    r")\b",
    re.I,
)

_EMAIL_IN_ANGLE = re.compile(r"<([^>]+@[^>]+)>")


def extract_email_address(sender: str) -> str:
    text = (sender or "").strip()
    if not text:
        return ""
    match = _EMAIL_IN_ANGLE.search(text)
    if match:
        return match.group(1).strip().lower()
    if "@" in text:
        return text.strip().lower()
    return ""


def extract_domain(sender: str) -> str:
    addr = extract_email_address(sender)
    if "@" not in addr:
        return ""
    return addr.rsplit("@", 1)[-1].lower()


def is_allowlisted(sender: str, extra_domains: tuple[str, ...] = ()) -> bool:
    domain = extract_domain(sender)
    if not domain:
        return False
    domains = ALLOWLIST_DOMAINS + extra_domains
    for allowed in domains:
        if domain == allowed or domain.endswith("." + allowed):
            return True
    return False


def should_keep_mail(record: dict[str, Any], *, extra_domains: tuple[str, ...] = ()) -> tuple[bool, str]:
    """Return (keep, reason). reason is useful for tests and sync stats."""
    labels = {str(item) for item in (record.get("labels") or [])}
    if labels & HARD_EXCLUDE_LABELS:
        return False, "hard_label"

    sender = str(record.get("sender") or "")
    if is_allowlisted(sender, extra_domains):
        return True, "allowlist"

    if labels & SOFT_EXCLUDE_LABELS:
        return False, "category"

    subject = str(record.get("subject") or "")
    if _PROMO_SUBJECT.search(subject):
        return False, "promo_heuristic"

    return True, "ok"
