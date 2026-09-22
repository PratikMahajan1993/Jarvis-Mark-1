from pathlib import Path

from dotenv import load_dotenv
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent  # repo root; README.md and .cursor/environment.json both launch uvicorn from here.
load_dotenv(ROOT.parent / ".env", override=True)
load_dotenv(ROOT / ".env", override=False)


def _anchor_to_repo_root(path: Path) -> Path:
    """Resolve a possibly-relative path against REPO_ROOT, never the process CWD.

    `.env` ships DATA_DIR=./data and EXPORTS_DIR=./exports as relative strings. A relative
    Path resolves against whatever directory the process happens to be launched from, so the
    same setting silently pointed at `backend/data` or `<repo>/data` depending on the caller's
    CWD. Anchoring here makes the on-disk location depend only on the repo, not the launch site.
    """
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        extra="ignore",
        env_file=(ROOT.parent / ".env", ROOT / ".env"),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
    )

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    llm_provider: str = "auto"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.6-flash"
    gemini_drawing_model: str = "gemini-3.1-pro"
    jarvis_host: str = "0.0.0.0"
    jarvis_port: int = 8000
    cors_origins: str = "http://localhost:3000"
    data_dir: Path = REPO_ROOT / "data"
    exports_dir: Path = REPO_ROOT / "exports"
    # Unset by default; resolved to data_dir/canvas below once data_dir is known.
    canvas_dir: Path | None = None
    google_cse_api_key: str = ""
    google_cse_cx: str = ""
    tavily_api_key: str = ""
    brave_api_key: str = ""
    email_backend: str = "local"
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    calendar_backend: str = "local"
    tz: str = "Asia/Kolkata"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_client_json: str = ""
    google_redirect_uri: str = "http://127.0.0.1:8000/api/google/callback"
    google_account: str = "pgeneration.mech@gmail.com"
    gemini_task_to: str = "pgeneration.mech@gmail.com"
    hud_url: str = "http://localhost:3000"
    hermes_enabled: bool = True
    hermes_bin: str = "hermes"
    hermes_home: str = ""
    hermes_timeout_sec: float = 30.0
    hermes_mcp_name: str = "jarvis"
    # Warm Hermes API server (hermes gateway). Prefer over CLI --oneshot.
    hermes_gateway_url: str = "http://127.0.0.1:8642"
    hermes_api_key: str = ""
    hermes_prefer_gateway: bool = True

    # Local Voicebox TTS (https://voicebox.sh/) — desktop app on :17493
    voicebox_enabled: bool = True
    voicebox_url: str = "http://127.0.0.1:17493"
    voicebox_profile: str = "Mark"
    voicebox_timeout_sec: float = 45.0

    # Turn ledger (accept-then-work); dark until HUD reconciles against server rows.
    turn_ledger_enabled: bool = False

    # Master data (parties/materials/suppliers); default off — dual-read with client-names.md.
    masterdata_enabled: bool = False

    @field_validator("data_dir", "exports_dir", mode="after")
    @classmethod
    def _anchor_data_paths(cls, value: Path) -> Path:
        return _anchor_to_repo_root(value)

    @model_validator(mode="after")
    def _resolve_canvas_dir(self) -> "Settings":
        # CANVAS_DIR is rarely set explicitly; default it under data_dir so it moves with
        # DATA_DIR overrides instead of pointing at a separate, disconnected tree.
        self.canvas_dir = _anchor_to_repo_root(self.canvas_dir) if self.canvas_dir else self.data_dir / "canvas"
        return self

    @property
    def origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jarvis.db"


settings = Settings()
assert settings.canvas_dir is not None
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir.mkdir(parents=True, exist_ok=True)
settings.canvas_dir.mkdir(parents=True, exist_ok=True)
