from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT.parent / ".env", override=True)
load_dotenv(ROOT / ".env", override=False)


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
    data_dir: Path = ROOT / "data"
    exports_dir: Path = ROOT / "exports"
    canvas_dir: Path = ROOT / "data" / "canvas"
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

    @property
    def origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jarvis.db"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
settings.exports_dir.mkdir(parents=True, exist_ok=True)
settings.canvas_dir.mkdir(parents=True, exist_ok=True)
