from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/vidflow"

    @field_validator("DATABASE_URL")
    @classmethod
    def fix_db_url(cls, v: str) -> str:
        # Railway (and Heroku) provide postgres:// or plain postgresql:// — convert for asyncpg
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    # APIs
    GEMINI_API_KEY: str = ""
    PEXELS_API_KEY: str = ""
    PIXABAY_API_KEY: str = ""

    # App
    SECRET_KEY: str = "change-me-in-production-very-long-secret-key"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    UPLOAD_DIR: str = "/tmp/vidflow_uploads"
    OUTPUT_DIR: str = "/tmp/vidflow_outputs"
    VIDFLOW_STORAGE_DIR: str = "/tmp/vidflow_storage"

    # TTS
    TTS_PROVIDER: str = "edge_tts"
    EDGE_TTS_VOICE_AR: Optional[str] = None
    EDGE_TTS_VOICE_EN: Optional[str] = None
    EDGE_TTS_VOICE_TR: Optional[str] = None
    EDGE_TTS_VOICE: Optional[str] = None

    # Optional external services
    N8N_WEBHOOK_URL: Optional[str] = None
    WHATSAPP_NUMBER: Optional[str] = None

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
