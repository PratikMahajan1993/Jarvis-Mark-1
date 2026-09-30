from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from ..config import settings

os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"
GMAIL_READONLY = "https://www.googleapis.com/auth/gmail.readonly"
DRIVE_FILE = "https://www.googleapis.com/auth/drive.file"
CALENDAR_EVENTS = "https://www.googleapis.com/auth/calendar.events"
CALENDAR_READONLY = "https://www.googleapis.com/auth/calendar.readonly"
CALENDAR_FULL = "https://www.googleapis.com/auth/calendar"
SPREADSHEETS = "https://www.googleapis.com/auth/spreadsheets"

SCOPES = (
    GMAIL_SEND,
    GMAIL_READONLY,
    DRIVE_FILE,
    CALENDAR_EVENTS,
    CALENDAR_READONLY,
    SPREADSHEETS,
)

# Two accounts only: existing shop token + one staff token. Filenames stay under data/.
ACCOUNT_TOKEN_FILES: dict[str, str] = {
    "shop": "google_token.json",
    "staff": "google_token_staff.json",
}


def normalize_account(account: str | None = None) -> str:
    label = (account or "shop").strip().lower() or "shop"
    if label not in ACCOUNT_TOKEN_FILES:
        raise ValueError(f"Unknown Google account {label!r}. Use shop or staff.")
    return label


def token_path(account: str | None = None) -> Path:
    return settings.data_dir / ACCOUNT_TOKEN_FILES[normalize_account(account)]


def state_path() -> Path:
    return settings.data_dir / "google_oauth_state.json"


def configured() -> bool:
    if settings.google_client_id and settings.google_client_secret:
        return True
    path = Path(settings.google_client_json) if settings.google_client_json else None
    return bool(path and path.is_file())


def connected(account: str | None = None) -> bool:
    path = token_path(account)
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("refresh_token") or data.get("token"))


def _client_config() -> dict[str, Any]:
    if settings.google_client_json:
        path = Path(settings.google_client_json)
        raw = json.loads(path.read_text(encoding="utf-8"))
        key = "web" if "web" in raw else "installed"
        raw[key]["redirect_uris"] = [settings.google_redirect_uri]
        return raw
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def auth_url(account: str | None = None) -> str:
    from google_auth_oauthlib.flow import Flow

    label = normalize_account(account)
    if not configured():
        raise RuntimeError("Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
    flow = Flow.from_client_config(_client_config(), scopes=list(SCOPES), redirect_uri=settings.google_redirect_uri)
    login_hint = settings.google_account if label == "shop" else None
    url, state = flow.authorization_url(
        access_type="offline",
        # Do not merge scopes from other apps sharing this OAuth client (e.g. YouTube
        # uploader + drive.file triggers Google "invalid_request" 400).
        include_granted_scopes="false",
        prompt="consent",
        login_hint=login_hint or None,
    )
    state_path().parent.mkdir(parents=True, exist_ok=True)
    state_path().write_text(
        json.dumps({"state": state, "code_verifier": flow.code_verifier, "account": label}),
        encoding="utf-8",
    )
    return url


def finish_auth(code: str, state: str = "") -> str:
    from google_auth_oauthlib.flow import Flow

    saved = {}
    if state_path().is_file():
        try:
            saved = json.loads(state_path().read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            saved = {}
    if state and saved.get("state") and state != saved["state"]:
        raise RuntimeError("OAuth state mismatch. Start Connect Gmail again.")
    verifier = saved.get("code_verifier")
    if not verifier:
        raise RuntimeError("OAuth session expired. Start Connect Gmail again.")
    label = normalize_account(str(saved.get("account") or "shop"))
    flow = Flow.from_client_config(_client_config(), scopes=list(SCOPES), redirect_uri=settings.google_redirect_uri)
    flow.code_verifier = verifier
    flow.fetch_token(code=code, code_verifier=verifier)
    path = token_path(label)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(flow.credentials.to_json(), encoding="utf-8")
    if state_path().is_file():
        state_path().unlink()
    return label


def token_scopes(account: str | None = None) -> list[str]:
    path = token_path(account)
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw = data.get("scopes") or []
    if isinstance(raw, str):
        return [item for item in raw.split() if item]
    if isinstance(raw, list):
        return [str(item) for item in raw if item]
    return []


def has_calendar(account: str | None = None) -> bool:
    granted = set(token_scopes(account))
    return bool(granted & {CALENDAR_EVENTS, CALENDAR_FULL, CALENDAR_READONLY})


def has_calendar_list(account: str | None = None) -> bool:
    granted = set(token_scopes(account))
    return bool(granted & {CALENDAR_FULL, CALENDAR_READONLY})


def has_sheets(account: str | None = None) -> bool:
    granted = set(token_scopes(account))
    return SPREADSHEETS in granted


def credentials(account: str | None = None):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    label = normalize_account(account)
    path = token_path(label)
    if not path.is_file():
        return None
    granted = token_scopes(label) or list(SCOPES)
    creds = Credentials.from_authorized_user_file(str(path), scopes=granted)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        path.write_text(creds.to_json(), encoding="utf-8")
    return creds if creds and creds.valid else None


def google_service(api: str, version: str, account: str | None = None):
    from googleapiclient.discovery import build

    label = normalize_account(account)
    creds = credentials(label)
    if not creds:
        raise RuntimeError("Gmail is not connected." if label == "shop" else f"Google account {label!r} is not connected.")
    return build(api, version, credentials=creds, cache_discovery=False)


def account_status(account: str | None = None) -> dict[str, Any]:
    label = normalize_account(account)
    return {
        "label": label,
        "token_filename": ACCOUNT_TOKEN_FILES[label],
        "connected": connected(label),
        "calendar": has_calendar(label),
        "calendar_list": has_calendar_list(label),
        "sheets": has_sheets(label),
    }


def status() -> dict[str, Any]:
    shop = account_status("shop")
    staff = account_status("staff")
    return {
        "configured": configured(),
        "connected": shop["connected"],
        "calendar": shop["calendar"],
        "calendar_list": shop["calendar_list"],
        "sheets": shop["sheets"],
        "account": settings.google_account,
        "task_to": settings.gemini_task_to or settings.google_account,
        "accounts": {
            "shop": shop,
            "staff": staff,
        },
    }
