from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..config import settings

SCOPES = (
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/drive.file",
)


def token_path() -> Path:
    return settings.data_dir / "google_token.json"


def state_path() -> Path:
    return settings.data_dir / "google_oauth_state.json"


def configured() -> bool:
    if settings.google_client_id and settings.google_client_secret:
        return True
    path = Path(settings.google_client_json) if settings.google_client_json else None
    return bool(path and path.is_file())


def connected() -> bool:
    path = token_path()
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


def auth_url() -> str:
    from google_auth_oauthlib.flow import Flow

    if not configured():
        raise RuntimeError("Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")
    flow = Flow.from_client_config(_client_config(), scopes=list(SCOPES), redirect_uri=settings.google_redirect_uri)
    url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        login_hint=settings.google_account or None,
    )
    state_path().write_text(json.dumps({"state": state}), encoding="utf-8")
    return url


def finish_auth(code: str, state: str = "") -> None:
    from google_auth_oauthlib.flow import Flow

    saved = {}
    if state_path().is_file():
        try:
            saved = json.loads(state_path().read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            saved = {}
    if state and saved.get("state") and state != saved["state"]:
        raise RuntimeError("OAuth state mismatch.")
    flow = Flow.from_client_config(_client_config(), scopes=list(SCOPES), redirect_uri=settings.google_redirect_uri)
    flow.fetch_token(code=code)
    token_path().write_text(flow.credentials.to_json(), encoding="utf-8")
    if state_path().is_file():
        state_path().unlink()


def credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not token_path().is_file():
        return None
    creds = Credentials.from_authorized_user_file(str(token_path()), scopes=list(SCOPES))
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path().write_text(creds.to_json(), encoding="utf-8")
    return creds if creds and creds.valid else None


def google_service(api: str, version: str):
    from googleapiclient.discovery import build

    creds = credentials()
    if not creds:
        raise RuntimeError("Gmail is not connected.")
    return build(api, version, credentials=creds, cache_discovery=False)


def status() -> dict[str, Any]:
    return {
        "configured": configured(),
        "connected": connected(),
        "account": settings.google_account,
        "task_to": settings.gemini_task_to or settings.google_account,
    }
